"""
auth-service/tests/test_security_jwt.py — JWT cryptographic security tests.

Tests cover four active attack vectors against POST /verify and one passive
check that documents a missing startup control (JWT_SECRET validation).

Active tests all currently PASS because python-jose + the algorithms=["HS256"]
constraint in app.py already rejects each attack variant.  The fifth test
(test_jwt_secret_not_default) currently FAILS (XFAIL) because no startup guard
for the insecure default value exists.

Run with:
    python3 -m pytest auth-service/tests/test_security_jwt.py -v
"""

import base64
import importlib.util
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from jose import jwt

# ---------------------------------------------------------------------------
# Path setup — auth-service/ and shared/ must be on sys.path before any
# service code is imported.  Matches conftest.py exactly.
# ---------------------------------------------------------------------------
_here = Path(__file__).resolve()
_auth_dir = _here.parent.parent            # u-vote/auth-service/
_shared_dir = _auth_dir.parent / "shared"  # u-vote/shared/

for _p in [str(_shared_dir), str(_auth_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the module already loaded by conftest.py when present; load fresh
# otherwise.  Avoids a second exec of app.py which would create a duplicate
# Prometheus registry.
_AUTH_MODULE = "auth_service_app"
if _AUTH_MODULE not in sys.modules:
    _spec = importlib.util.spec_from_file_location(_AUTH_MODULE, _auth_dir / "app.py")
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_AUTH_MODULE] = _mod
    _spec.loader.exec_module(_mod)

_app_module = sys.modules[_AUTH_MODULE]
app          = _app_module.app
JWT_SECRET   = _app_module.JWT_SECRET    # app.py:59
JWT_ALGORITHM = _app_module.JWT_ALGORITHM  # app.py:60  ("HS256")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_jwt_algorithm_none_attack():
    """Algorithm-confusion attack: crafts a JWT with alg=none and no signature.

    Attack: the attacker sets the header's alg field to "none" and omits the
    signature entirely (trailing dot with empty string).  A library that trusts
    the header's alg field without checking an allow-list will accept the token
    and return the arbitrary claims inside it — no secret key required.

    Defence: app.py passes algorithms=["HS256"] to jose.jwt.decode() (app.py
    line ~147).  python-jose rejects any token whose alg claim is not in that
    list, raising JWTError, which the route maps to HTTP 401.
    """
    header_b64 = (
        base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    payload_b64 = (
        base64.urlsafe_b64encode(
            json.dumps({"organiser_id": 1, "email": "evil@attacker.com"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    # alg=none format: header.payload.  (empty signature part after final dot)
    alg_none_token = f"{header_b64}.{payload_b64}."

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/verify", json={"token": alg_none_token})

    assert resp.status_code == 401, (
        f"Expected 401 for alg=none token, got {resp.status_code}.  "
        "python-jose must reject alg=none when algorithms=['HS256'] is specified."
    )


@pytest.mark.asyncio
async def test_jwt_tampered_payload_rejected():
    """Signature-stripping / payload-tampering attack.

    Attack: the attacker obtains a valid, legitimately signed JWT, decodes the
    base64url payload without verifying the signature, modifies a privileged
    claim (e.g. escalates organiser_id from 1 to 999), re-encodes the payload,
    and reassembles the three-part token keeping the ORIGINAL signature.  A
    vulnerable implementation that skips signature verification would grant the
    attacker's forged claims.

    Defence: HMAC-SHA256 covers the concatenated bytes of header + "." +
    payload.  Changing the payload invalidates the MAC; jose.jwt.decode() raises
    JWTError, and the /verify route returns HTTP 401.
    """
    now = int(time.time())
    original_payload = {
        "organiser_id": 1,
        "email": "admin@uvote.com",
        "exp": now + 3600,
    }
    valid_token = jwt.encode(original_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    # Split into the three base64url parts.
    header_b64, _, sig_b64 = valid_token.split(".")

    # Re-encode the payload with an escalated organiser_id — keep original sig.
    tampered_payload = dict(original_payload)
    tampered_payload["organiser_id"] = 999
    new_payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(tampered_payload).encode())
        .rstrip(b"=")
        .decode()
    )
    tampered_token = f"{header_b64}.{new_payload_b64}.{sig_b64}"

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/verify", json={"token": tampered_token})

    assert resp.status_code == 401, (
        f"Expected 401 for tampered-payload token, got {resp.status_code}.  "
        "The HMAC signature must cover the full header.payload bytes."
    )


@pytest.mark.asyncio
async def test_expired_jwt_rejected():
    """Expired token must be rejected even when the signature is valid.

    Attack: a token that was valid in the past (or was stolen) should not grant
    access after its expiry time.  An implementation that verifies the signature
    but ignores the exp claim would allow indefinite use of leaked tokens.

    Defence: jose.jwt.decode() automatically validates the exp claim against the
    current UTC time; a token with exp in the past raises JWTError("Signature has
    expired"), which app.py's except block maps to HTTP 401 with detail "Token
    expired".
    """
    expired_payload = {
        "organiser_id": 1,
        "email": "admin@uvote.com",
        "exp": int(time.time()) - 10,  # 10 seconds in the past
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/verify", json={"token": expired_token})

    assert resp.status_code == 401, (
        f"Expected 401 for expired token, got {resp.status_code}."
    )


@pytest.mark.asyncio
async def test_jwt_signed_with_wrong_secret_rejected():
    """Token signed with a different secret key must be rejected.

    Attack: a party who knows the JWT structure (header + payload format) but
    not the server's secret attempts to forge a valid token by signing it with
    any arbitrary key.  A vulnerable implementation that skips signature
    verification would accept any well-formed JWT regardless of the signing key.

    Defence: HMAC-SHA256 verification requires knowledge of the exact secret.
    jose.jwt.decode() computes the expected MAC with JWT_SECRET and rejects any
    token whose signature does not match, raising JWTError → HTTP 401.
    """
    forged_payload = {
        "organiser_id": 1,
        "email": "admin@uvote.com",
        "exp": int(time.time()) + 3600,
    }
    forged_token = jwt.encode(forged_payload, "wrong-secret", algorithm=JWT_ALGORITHM)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/verify", json={"token": forged_token})

    assert resp.status_code == 401, (
        f"Expected 401 for token signed with wrong secret, got {resp.status_code}."
    )


@pytest.mark.xfail(
    reason=(
        "auth-service/app.py has no startup guard against the insecure default "
        "JWT_SECRET value — see docstring for the missing control"
    ),
)
def test_jwt_secret_not_default():
    """Verify that JWT_SECRET has been changed from the insecure default value.

    Missing control: app.py line 59 reads:
        JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    with no subsequent validation.  The service starts successfully with the
    default value, silently accepting tokens signed by any party who knows it
    (the value is publicly visible in the repository).

    Expected behaviour: the lifespan function should refuse to start when
    JWT_SECRET equals the default.  Example guard to add inside lifespan():

        if JWT_SECRET == "your-secret-key-change-in-production":
            raise RuntimeError(
                "JWT_SECRET must be changed from the default value "
                "before running in any environment."
            )

    This test is marked xfail because JWT_SECRET is the default in the test
    environment (no JWT_SECRET env var is set) and no guard exists.  Once the
    guard is added, update this test to call the lifespan or the validation
    function directly and remove the xfail marker.
    """
    insecure_default = "your-secret-key-change-in-production"

    # In the unpatched test environment JWT_SECRET takes the default value from
    # os.getenv().  This assertion documents the missing control: it fails
    # (XFAIL) until a startup guard is added to app.py.
    assert _app_module.JWT_SECRET != insecure_default, (
        f"JWT_SECRET equals the insecure default '{insecure_default}'.  "
        "Add a RuntimeError guard in the lifespan function to prevent the "
        "service from starting with this value."
    )
