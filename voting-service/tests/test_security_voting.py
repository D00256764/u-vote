"""
voting-service/tests/test_security_voting.py — ballot integrity security tests.

Three tests cover the core one-time-token attack surface of POST /vote/submit:
  1. Replay           — reusing a spent ballot token sequentially
  2. Double-spend     — two concurrent requests with the same token
  3. Token forgery    — submitting a randomly generated token never issued

Implementation note — HTTP status codes:
  POST /vote/submit always returns HTTP 200 (HTMLResponse).  Error conditions
  are rendered into vote_error.html rather than returned as 4xx codes.
  Assertions therefore check response body content.  The ideal REST design
  would return 400 or 409 for rejection cases; this is noted in each docstring.

Run with:
    .venv/bin/python -m pytest voting-service/tests/test_security_voting.py -v
"""

import asyncio
import importlib.util
import os
import secrets
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

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

    # Fix template and static-file paths to absolute so rendering works
    # regardless of CWD (same fix applied by conftest.py).
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
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_voting_token_replay_after_use(
    mock_db,
    valid_ballot_token_row,
    valid_election_row,
    valid_option_row,
):
    """Replay attack: a voter submits their ballot then immediately replays the
    identical POST /vote/submit request to attempt a second vote.

    One-time ballot tokens are the primary integrity control that links the
    anonymous voting act to a single authorised voter.  Without replay
    protection, a single token would allow unlimited vote injection.

    Defence: app.py reads blind_tokens.is_used inside a FOR UPDATE transaction
    (app.py line ~237-249).  When the first submission completes it sets
    is_used = TRUE; the replayed request reads the updated row and returns the
    error page "This ballot token has already been used".

    Note: POST /vote/submit always returns HTTP 200 (HTMLResponse).  The ideal
    API design would return HTTP 400 on replay; the current HTML interface
    embeds the rejection message in vote_error.html instead.
    """
    # First submission — five fetchrow calls in submit_vote order:
    #   1. blind_tokens lookup (token valid, unused)
    #   2. elections (open, has encryption key)
    #   3. election_options (option belongs to election)
    #   4. encrypted_ballots — previous hash for hash chain
    #   5. encrypted_ballots — ballot_hash set by DB trigger after INSERT
    # Replay — blind_tokens lookup now returns is_used=True
    mock_db.fetchrow.side_effect = [
        valid_ballot_token_row,                          # 1 blind_tokens — unused
        valid_election_row,                              # 2 elections
        valid_option_row,                                # 3 election_options
        None,                                            # 4 no previous hash
        {"ballot_hash": "hash-first-vote"},              # 5 ballot_hash
        {**valid_ballot_token_row, "is_used": True},     # replay: token spent
    ]

    form = {
        "ballot_token": valid_ballot_token_row["ballot_token"],
        "option_id": str(valid_option_row["id"]),
        "election_id": str(valid_election_row["id"]),
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first_resp  = await client.post("/vote/submit", data=form)
        replay_resp = await client.post("/vote/submit", data=form)

    assert "Vote Submitted" in first_resp.text, (
        "First vote should succeed; got unexpected body: "
        f"{first_resp.text[:300]}"
    )
    assert "already been used" in replay_resp.text, (
        "Expected replay to be rejected with 'already been used' in HTML body; "
        f"got: {replay_resp.text[:300]}"
    )


@pytest.mark.asyncio
async def test_ballot_token_double_spend_concurrent(
    mock_db,
    valid_ballot_token_row,
    valid_election_row,
    valid_option_row,
):
    """Double-spend attack: two concurrent POST /vote/submit requests using the
    same ballot token, submitted before the first can mark the token used.

    Attack: an attacker who intercepts a ballot token fires two simultaneous
    requests in the race window between the blind_tokens READ and the
    subsequent is_used = TRUE UPDATE.  If no row-level lock is held, both
    transactions read is_used=FALSE, both proceed, and the election tally is
    inflated by one extra phantom vote.

    Defence: app.py acquires SELECT ... FOR UPDATE on blind_tokens before
    reading is_used (app.py line ~237).  The second concurrent transaction
    blocks on the lock until the first commits; it then reads is_used=TRUE and
    is rejected.  This serialises concurrent submissions of the same token.

    Limitation of this mock-based test: AsyncMock returns values immediately
    without yielding to the event loop, so asyncio.gather runs the two ASGI
    requests sequentially rather than truly interleaved.  The mocked database
    also has no transactional state — it returns is_used=FALSE for both
    requests' blind_tokens lookups regardless of what the first request wrote.
    Both requests therefore return "Vote Submitted", causing the assertion
    below to FAIL.  This failure is intentional: it signals that the FOR UPDATE
    lock can only be verified in integration tests against a real PostgreSQL
    instance.
    """
    TOKEN = valid_ballot_token_row["ballot_token"]

    # Five fetchrow values per request.  Both requests see is_used=False on
    # the blind_tokens lookup because the mock has no transactional memory —
    # this simulates the race window the attack exploits.
    mock_db.fetchrow.side_effect = [
        # Request 1 — 5 fetchrow calls
        {**valid_ballot_token_row, "is_used": False},   # blind_tokens (race: False)
        valid_election_row,                              # elections
        valid_option_row,                                # election_options
        None,                                            # no previous hash
        {"ballot_hash": "hash-A"},                       # ballot_hash after INSERT
        # Request 2 — mock returns False again; real DB would block on lock
        {**valid_ballot_token_row, "is_used": False},   # blind_tokens (race: False)
        valid_election_row,                              # elections
        valid_option_row,                                # election_options
        None,                                            # no previous hash
        {"ballot_hash": "hash-B"},                       # ballot_hash after INSERT
    ]

    form = {
        "ballot_token": TOKEN,
        "option_id": str(valid_option_row["id"]),
        "election_id": str(valid_election_row["id"]),
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp1, resp2 = await asyncio.gather(
            client.post("/vote/submit", data=form),
            client.post("/vote/submit", data=form),
        )

    success_count = sum(
        1 for r in (resp1, resp2) if "Vote Submitted" in r.text
    )
    assert success_count == 1, (
        f"CRITICAL double-spend: {success_count} out of 2 concurrent requests "
        f"with ballot token '{TOKEN}' both returned 'Vote Submitted'.  "
        "One request must be rejected.  "
        "The FOR UPDATE lock on blind_tokens serialises concurrent token "
        "consumption under real PostgreSQL concurrency but cannot be "
        "reproduced with mock-based testing — add integration tests against "
        "a live database to validate the locking behaviour."
    )


@pytest.mark.asyncio
async def test_ballot_token_invalid_rejected(mock_db):
    """Token forgery: submitting a randomly generated ballot token that was
    never issued to any voter by auth-service.

    Attack: an attacker who knows the POST /vote/submit endpoint tries random
    token strings, attempting to cast votes without having gone through the
    MFA and token-issuance flow.  Success would allow arbitrary vote injection
    with no valid identity.

    Defence: app.py queries blind_tokens WHERE ballot_token = $1 AND
    election_id = $2 (app.py line ~237).  A token never inserted by
    auth-service's POST /ballot-token/issue will not match any row; fetchrow
    returns None and the route renders _error_page("Invalid ballot token").

    Note: POST /vote/submit always returns HTTP 200 (HTMLResponse).  The ideal
    REST API design would return HTTP 400 or 403 for an unrecognised token; the
    current HTML interface embeds the rejection in vote_error.html instead.
    """
    # Simulate the token not existing in blind_tokens
    mock_db.fetchrow.return_value = None

    forged_token = secrets.token_hex(32)  # 64-char hex string never issued

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/vote/submit",
            data={
                "ballot_token": forged_token,
                "option_id": "1",
                "election_id": "1",
            },
        )

    assert "Invalid ballot token" in resp.text, (
        "Expected 'Invalid ballot token' in response body for a forged token; "
        f"got: {resp.text[:300]}"
    )
