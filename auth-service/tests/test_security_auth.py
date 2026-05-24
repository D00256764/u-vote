"""
auth-service/tests/test_security_auth.py — rate-limiting / brute-force security tests.

These tests document the EXPECTED behaviour once rate-limiting middleware is added
to the /login and /mfa/verify routes.  All three tests currently fail because no
rate-limiting is implemented in auth-service/app.py.

Run with:
    python3 -m pytest auth-service/tests/test_security_auth.py -v
"""

import importlib.util
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Path setup — auth-service/ and shared/ must be on sys.path before any
# service code is imported.
# ---------------------------------------------------------------------------
_here = Path(__file__).resolve()
_auth_dir = _here.parent.parent            # u-vote/auth-service/
_shared_dir = _auth_dir.parent / "shared"  # u-vote/shared/

for _p in [str(_shared_dir), str(_auth_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the module already loaded by conftest.py when present; load fresh
# otherwise.  This avoids a second exec of app.py under a different module
# name which would create a duplicate Prometheus registry.
_AUTH_MODULE = "auth_service_app"
if _AUTH_MODULE not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_AUTH_MODULE, _auth_dir / "app.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_AUTH_MODULE] = _mod
    _spec.loader.exec_module(_mod)

app = sys.modules[_AUTH_MODULE].app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_brute_force_no_lockout(mock_db, seeded_organiser):
    """Send 20 consecutive wrong-password requests to POST /login and assert
    that the 20th attempt returns HTTP 429 (Too Many Requests) or HTTP 423
    (Locked).

    EXPECTED TO FAIL: No rate-limiting middleware exists on /login.  Every
    attempt returns 401 Unauthorized indefinitely.  This test will pass once
    slowapi or fastapi-limiter is added to the /login route with an attempt
    threshold of ≤ 20 requests per window.
    """
    mock_db.fetchrow.return_value = seeded_organiser

    last_status: int | None = None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for _ in range(20):
            resp = await client.post(
                "/login",
                json={"email": "admin@uvote.com", "password": "WrongPass999!"},
            )
            last_status = resp.status_code

    assert last_status in (429, 423), (
        f"Expected HTTP 429 or 423 after 20 failed login attempts, "
        f"got {last_status}.  "
        "Rate-limiting middleware is not yet implemented on POST /login."
    )


@pytest.mark.asyncio
async def test_otp_brute_force_rate_limited(mock_db):
    """Cycle through sequential 6-digit OTPs (000000–000999) on
    POST /mfa/verify and assert that HTTP 429 is returned before all 1,000
    attempts are exhausted.  The loop breaks on the first 429; the test fails
    if no 429 was received.

    EXPECTED TO FAIL: No rate-limiting on /mfa/verify.  All 1,000 attempts
    return 401 (wrong OTP) without triggering a lockout.  This test will pass
    once a rate limit is added to /mfa/verify with a threshold well below
    1,000 attempts.
    """
    mock_db.fetchrow.return_value = {
        "voter_id": 10,
        "has_voted": False,
        "is_used": False,
        "expires_at": datetime(2030, 1, 1),
        "status": "open",
        "election_id": 5,
        # OTP that is unreachable within the 000000–000999 iteration range,
        # so every attempt in the loop returns 401 rather than 200.
        "otp_code": "999999",
        "otp_expires_at": datetime(2030, 1, 1),
        "verified_at": None,
    }

    got_429 = False
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for i in range(1000):
            resp = await client.post(
                "/mfa/verify",
                params={"token": "voter-token-fixture", "otp": f"{i:06d}"},
            )
            if resp.status_code == 429:
                got_429 = True
                break

    assert got_429, (
        "Expected HTTP 429 before exhausting 1,000 OTP attempts. "
        "Rate-limiting is not yet implemented on POST /mfa/verify."
    )


@pytest.mark.asyncio
async def test_login_rate_limit_resets_after_timeout(mock_db, seeded_organiser):
    """Trigger a /login lockout via repeated wrong-password requests, advance
    time past the lockout window, then assert that correct credentials return
    HTTP 200.

    EXPECTED TO FAIL: This test depends on two things that are absent from the
    current implementation:
      (1) A configurable rate-limit window on POST /login (e.g. slowapi with a
          per-IP limiter and an explicit lockout duration).
      (2) The lockout window being mockable via patch("time.time", ...) or
          freezegun so that the test does not need to sleep.

    The assertion that the lockout was triggered (Step 1 below) will fail
    immediately since the route never returns 429, making the time-advance
    step unreachable until rate-limiting is added.
    """
    LOCKOUT_THRESHOLD = 5  # number of failed attempts before lockout expected

    mock_db.fetchrow.return_value = seeded_organiser

    lockout_triggered = False
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Step 1: flood /login with wrong passwords to trigger lockout.
        for _ in range(LOCKOUT_THRESHOLD + 1):
            resp = await client.post(
                "/login",
                json={"email": "admin@uvote.com", "password": "WrongPass999!"},
            )
            if resp.status_code in (429, 423):
                lockout_triggered = True
                break

        assert lockout_triggered, (
            f"Expected HTTP 429 or 423 within {LOCKOUT_THRESHOLD + 1} failed "
            "login attempts.  Add slowapi/fastapi-limiter to POST /login first."
        )

        # Step 2: advance time by 120 s to expire the lockout window, then
        # confirm a correct password is accepted again.
        with patch("time.time", return_value=time.time() + 120):
            mock_db.fetchrow.return_value = seeded_organiser
            resp = await client.post(
                "/login",
                json={"email": "admin@uvote.com", "password": "admin123"},
            )

    assert resp.status_code == 200, (
        f"Expected HTTP 200 after lockout window expired, got {resp.status_code}."
    )
